# load libraries 
packages = c('furrr', 'goftest', 'tidyverse')
lapply(packages, require, character.only = T)

# define chi-squared pdf & cdf for homogeneous surfaces
intensity_pdf = function(I, mean_gamma_0, N=3.5) {
  (I^(N-1)*(N^N)*exp(-N*I/mean_gamma_0))/
  (factorial(N-1)*sqrt(mean_gamma_0)^(2*N))
}

intensity_cdf = function(I, mean_gamma_0) {
  round(integrate(f = intensity_pdf,
                  lower = 0,
                  upper = min(I,100),
                  mean_gamma_0 = mean_gamma_0)[[1]],
        5)
}

intensity_cdf = Vectorize(intensity_cdf)


# define goodness of fit tests
n_iter = 50
cvm_test = function(x) {
  multiple_p = map_dbl(
    .x = (1:n_iter),
    .f = ~cvm.test(
      x,
      null = intensity_cdf, 
      mean_gamma_0 = mean(x),
      estimated = T)$p.value
  )
  mean(multiple_p)
}

ad_test = function(x) {
  multiple_p = map_dbl(
    .x = (1:n_iter),
    .f = ~ad.test(
      x,
      null = intensity_cdf, 
      mean_gamma_0 = mean(x),
      estimated = T)$p.value
  )
  mean(multiple_p)
}

# note
# parallelisation with future map only with minor improvements
# n_cores_system <- parallel::detectCores()
# future::plan(multisession, workers = (n_cores_system-1))
# furrr_options(seed = T)
# future_map_dbl
# set.seed(42)